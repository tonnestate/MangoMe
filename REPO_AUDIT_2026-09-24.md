# MangoMe repository audit — 2026-09-24

Repository reviewed: `tonnestate/MangoMe` (`main`, v0.1.1 state visible on 2026-09-24)

## Executive result

MangoMe already has a coherent executable core. The central ideas are represented in code: family/contract identity, persistent slices, append-only contributions, plan-before-start, claims vs assurance, evidence, collision warnings, Big-Bang discovery, context compilation, MongoDB persistence, and execution economics.

It is **not yet complete enough to call the canonical truth layer production-safe for untrusted agents**. The main remaining risks are not cosmetic; they are around plan binding, identity/approval trust, evidence semantics, effective contract composition, and multi-family project explanation.

## P0 — fix before relying on MangoMe as authoritative production truth

### 1. Execution mutations are not consistently bound to an active plan

`start_slice()` requires a matching `plan_id`, but `update_slice_progress()` and `claim_done()` accept only `actor_id` and `slice_id`.

Consequences:

- a caller can mutate a slice after its plan was closed;
- an actor that never submitted a plan can update or claim completion if it knows the slice id;
- the invariant "plan before productive work" is only enforced at the first transition.

Recommended design:

- require `plan_id` for all productive slice mutations, or
- resolve exactly one active plan for `(actor_id, family_id)` and fail closed when zero/multiple active plans exist.

Do not introduce project locks. This is state-integrity binding, not work serialization.

### 2. Human approval is currently caller-declared, not trusted

The v0.1.1 integrity layer correctly models approvals, but MCP tools expose:

- `approve_override(approval_id, decided_by, ...)`
- `reject_override(...)`
- `accept_slice(..., accepted_by)`

`decided_by` / `accepted_by` are caller-supplied strings. An untrusted worker can therefore impersonate `human-owner` unless the MCP host enforces identity externally.

This is already documented, but it conflicts with the desired semantic guarantee that overrides/acceptance require real user approval.

Recommended design:

- keep `request_override` available to workers;
- bind decision identity to an authenticated MCP/runtime principal, never to a free-form tool argument;
- optionally disable decision tools by default unless a trusted approval provider is configured;
- retain `decision_ref` for provenance.

### 3. Evidence can be structurally present without being semantically strong enough

`_validate_evidence_ids()` rejects explicitly failing results, but otherwise any persisted evidence for the slice can support `PASS`.

Example risk:

```text
evidence_type = NOTE
result = "looks okay"
```

is not currently a failure result and could be used for a gate PASS.

Recommended design:

- add evidence assurance/state, e.g. `CLAIMED`, `OBSERVED`, `TESTED`, `VERIFIED`, `ATTESTED`;
- allow gates to define acceptable evidence types/levels;
- require deterministic test/runtime evidence for gates that declare it;
- make gate evaluators explicit rather than treating all non-failing evidence as equivalent.

### 4. Gate audit metadata is not in the canonical Pydantic schema

The integrity layer adds fields such as:

- `decided_by`
- `decided_at`
- `approval_id`

by directly patching gate dictionaries, while `models.Gate` does not define them.

This creates schema drift and the possibility that a future model round-trip silently drops audit metadata.

Recommended fix: add the fields to `Gate` and version the schema deliberately.

## P1 — core completeness gaps

### 5. No effective-family view yet

Contract contributions and typed edges exist, but MangoMe does not yet compute a deterministic effective family specification from:

```text
BASE + ADDITION + AMENDMENT + EXTENSION + REPAIR + explicit relations
```

`current_spec_id` points to one specification version; it is not the same thing as a compiled family truth from multiple contract contributions.

This is a central MangoMe capability and should be implemented before broad Big-Bang reconciliation.

### 6. Project-level overview is too thin

The service has `Project`, but status/context queries are family-centric. There is no strong deterministic equivalent of:

```text
project_overview(project_id)
```

that explains:

- all families in the project;
- related contracts;
- active/done-claimed/verified slice counts;
- open approvals;
- current actors;
- collision warnings;
- last project activity;
- unresolved relationships.

This matters because one of MangoMe's primary goals is being able to explain the state of an entire project to the user cheaply and deterministically.

### 7. Big-Bang discovery is not yet Big-Bang reconciliation

Current scanner limitations:

- filesystem text files only;
- fixed extension set;
- hard-coded contract-id prefixes (`AVCOS`, `TE`, `SPARI`, `COGC`, `CHOMVIEW`);
- no Git branches/history/worktrees/untracked adapter;
- no generalized configurable identifier grammar;
- no candidate clustering/family reconciliation step;
- no persisted reconciliation queue.

The scanner is useful, but the next stage must be a separate reconciliation pipeline rather than more regex.

Recommended escalation:

```text
structured metadata
→ parser
→ deterministic normalization
→ configurable lexical patterns
→ graph context
→ cheap classifier
→ strong model
→ user approval when still ambiguous
```

### 8. Relationship vocabulary and endpoints are not validated

`link()` currently accepts arbitrary relation text and does not verify that source/target entity ids exist in the declared entity types.

Add a typed relation vocabulary and endpoint validation. Suggested relations include:

```text
ADDS_TO
AMENDS
EXTENDS
REPAIRS
RECOVERS
SUPERSEDES
VALIDATES
IMPLEMENTS
PART_OF
IMPLEMENTED_IN
EXPOSED_BY
RELATES_TO
CONFLICTS_WITH
```

### 9. `schema_version` exists, but migration behavior does not

The repository correctly stores `schema_version`, but there is no migration registry/on-read upgrade path yet.

Add:

- per-collection current schema version;
- pure migration functions `vN -> vN+1`;
- lazy read migration or explicit maintainer migration;
- migration tests preserving historical documents.

### 10. Internal MongoDB concurrency needs revision/CAS protection

User-facing project collisions should remain warnings only. However, MangoMe's own canonical documents should not silently lose concurrent updates.

Add an internal `revision` or equivalent optimistic compare-and-set check for mutable materialized state/documents.

This protects MangoMe state without locking agent work.

### 11. Dependency semantics need an assurance policy

`next_known_slice_ids` currently treats a `DONE_CLAIMED` dependency as satisfied.

That may be correct for some execution dependencies, but not for work that must wait for verified assurance.

Recommended model:

```text
EXECUTION_DEPENDENCY   → DONE_CLAIMED is enough
ASSURANCE_DEPENDENCY   → VERIFIED/ACCEPTED required
```

### 12. Contract-id collision warnings are asymmetric across families

A duplicate declared contract ID is detected globally, but the warning is added only to the family being modified. If the duplicate exists in another family, the earlier family is not necessarily updated.

Prefer a global collision projection or refresh warnings for all affected families.

### 13. `import_slice()` silently returns an existing slice with the same declared id

If imported metadata/state differs, returning the existing object hides a potential conflict.

Compare imported and existing state and return a conflict result or create a reconciliation item.

### 14. Maintainer is still minimal

Current deterministic maintainer mainly refreshes views and detects contract-id collisions.

It should eventually handle:

- stale plans;
- stale active slices;
- unresolved relations;
- orphaned artifacts/edges;
- schema migration candidates;
- project rollups;
- collision projection refresh;
- optional re-scan scheduling.

No LLM is needed for most of this.

## P2 — repository / operational quality

### 15. Dotfiles are missing from the current GitHub tree

The current `main` tree does not contain:

```text
.github/workflows/ci.yml
.github/skills/mangome/SKILL.md
.gitignore
```

This happened because the upload path omitted dot-prefixed files/directories.

Effect:

- no GitHub Actions CI is currently running;
- no GitHub Agent Skill mirror is currently discoverable;
- ignore rules are not present in the repository.

The review pack contains these files again. Create/upload them explicitly by path.

### 16. README CLI syntax should follow current MCP v2 examples

Current official MCP Python SDK v2 documentation uses:

```bash
mcp dev server.py
mcp run server.py --transport streamable-http
```

The previous MangoMe README used `server.py:mcp`. The replacement README uses the current documented form.

### 17. Temporary patch artifacts should not become permanent repo surface

`PATCH_MANIFEST.md` is useful during manual upload but should probably be removed from the canonical public repository after the patch is applied.

`TEST_REPORT.md` is defensible, but a stable `docs/testing.md` is cleaner than a dated patch report once CI is live.

### 18. Public repository metadata can be improved

Recommended `pyproject.toml` additions:

```toml
[project.urls]
Homepage = "https://github.com/tonnestate/MangoMe"
Repository = "https://github.com/tonnestate/MangoMe"
Issues = "https://github.com/tonnestate/MangoMe/issues"
```

Optional later additions:

- Ruff/format checks;
- type checking;
- release/tag workflow;
- `.env.example`;
- `docs/deployment.md` with stdio/systemd guidance;
- `THIRD_PARTY_NOTICES.md` documenting architectural references and confirming whether code is bundled or only referenced.

### 19. MCP tests should exercise tools, not only import the server

The planned CI smoke test imports the MCP server, which is useful but shallow.

The MCP v2 client can connect directly to a server object in memory. Add an integration test that:

- lists tools;
- calls intake/family/spec/plan/start/progress/done/evidence/verify/status through MCP;
- verifies structured responses.

This tests tool registration and schemas as clients actually see them.

### 20. Add a health/readiness surface

For real deployment, add a deterministic health/readiness tool or resource reporting at least:

```text
service_version
backend
MongoDB ping
schema version
collections/index readiness
```

Do not make it an LLM-generated health assessment.

## Documentation findings

The previous README had good technical content but did not match the stronger public presentation already used by IntakeGov. It also buried the core proposition and mixed v0.1.0/v0.1.1 labeling.

The replacement README in this pack:

- uses the same centered tagline + badge header pattern as IntakeGov;
- makes MangoMe's problem statement explicit;
- explains slices and `last_started_slice_id` prominently;
- distinguishes claims, verification and acceptance;
- explains Big-Bang vs incremental onboarding;
- shows how IntakeGov, MangoMe, CogC and OmniRoute divide responsibilities;
- corrects MCP v2 CLI examples;
- includes an honest known-limitations section;
- adds a concrete roadmap instead of implying unfinished features already exist.

## Recommended implementation order

```text
1. Restore .github + .gitignore
2. Replace README
3. Bind all productive slice mutations to active plan
4. Establish trusted approval identity boundary
5. Put gate audit fields into canonical schema
6. Add evidence assurance / gate evidence policies
7. Add project_overview
8. Add effective_family_view
9. Validate graph relation vocabulary/endpoints
10. Add revision/CAS internal state protection
11. Build reconciliation pipeline over Big-Bang discovery
12. Add schema migration registry + maintainer expansion
13. Add external-provider reconciliation
14. Feed verified economic history back into routing/evals
```

## Bottom line

MangoMe is no longer merely a concept repository. It already contains the beginnings of a useful persistent multi-agent state system.

The remaining work is mainly about making its strongest claim true under pressure:

> MangoMe should be able to explain the current project truth even when workers disagree, sessions disappear, several agents work in parallel, contracts accumulate, and completion claims are unreliable.

The v0.1.1 core is pointed in that direction. The P0 items above are the next integrity boundary.
