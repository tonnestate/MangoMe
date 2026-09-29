# Structural Intelligence — MangoMe v0.3.11

MangoMe v0.3.11 adds bounded structural sight without creating a second truth system. Structural information is derived workspace observation only. It is never Contract truth, Evidence, Assurance, authority, WorkIdentity, or a normative baseline.

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

The implementation reuses RepoMap principles rather than absorbing Aider as an application: definitions/references, a dependency graph, centrality, task-conditioned ranking, incremental caching, and bounded rendering. Python uses the standard AST. Other supported programming languages use Tree-sitter through `tree-sitter-language-pack`; if a grammar is unavailable or parsing fails, MangoMe falls back to a bounded text parser and marks the observation partial. Parser/grammar work therefore cannot become a global MangoMe blocker.

The cache is process-local and disposable. File signatures are used for incremental refresh; a structural revision changes when the observed workspace changes. Canonical MangoMe state is not written by the structural subsystem.

## PCH, SRA, and ContextCompiler bridge

The normal worker facade can enrich `COGNITIVE_HYGIENE` with structural relevance. PCH may use this information to choose what is resident, but structural relevance never changes supportability, truth, or assurance.

`COMPILE_CONTEXT` first compiles canonical MangoMe execution context. Structural context is optional and is removed before canonical context if a transport budget would otherwise be exceeded. A `ContextBudgetExceeded` condition degrades to a minimal viable context before returning `CONTEXT_UNAVAILABLE`.

A `START_SCOPED_AUDIT` request may receive `structural_impact_candidates`. These candidates are explicitly `INSPECTION_CANDIDATES_ONLY`; the audit mutation boundary is unchanged.

## Operational boundary

The structural layer performs no LLM calls. It does not discover or admit WorkIdentity, does not restore canonical state, does not create Families/Specifications/Contracts, and does not issue verification or approval decisions.
