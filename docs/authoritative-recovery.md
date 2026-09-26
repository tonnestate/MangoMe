# Authoritative Recovery

MangoMe recovery is **state-first, not path-first**.

For admitted work, MangoMe already owns the durable identity and current operational state. A restarted worker or parent coordinator must not reconstruct a second version of that state by scanning directories, grepping contracts, reading worktree names, replaying Git archaeology, or inferring status from evidence folders.

The invariant is:

> **Recovery follows identity. Discovery must never create or reconstruct admitted identity/state.**

## Recovery order

```text
session_restore / session_bootstrap
    ↓
recovery_context
    ↓
project_overview / status
    ↓
effective_family_view / read_context
    ↓
bounded unresolved delta
    ↓
targeted artifact inspection
```

`recovery_context` is a deterministic projection of canonical MangoMe state. It includes the current specification, compact family status, active plans, recovery-relevant slices, known artifacts, known Evidence and open approvals. It does not derive identity from the filesystem.

## Discovery boundary

For an unknown workspace, filesystem and Big-Bang discovery remain useful onboarding mechanisms. Their results remain `CANDIDATE_ONLY` until current user intent or an explicit admission path creates canonical work.

For an admitted workspace:

- `bigbang_scan` must not be used as a recovery mechanism;
- broad `filesystem_scan` must not be used to reconstruct current work state;
- Big-Bang reconciliation must not rebuild admitted identity from discovered records;
- `filesystem_references` is limited to targeted validation of an identity MangoMe already knows;
- RB/1 reproduction bindings and Evidence freshness checks remain valid because they validate declared bindings rather than invent work identity.

The repository and filesystem remain observable reality. They are **not** the authority for reconstructing MangoMe's admitted work model.

## Coordinator recovery

A parent coordinator is not a replacement worker. In a delegated recovery program it should:

1. read canonical recovery state;
2. identify bounded unresolved deltas;
3. delegate mechanical reconstruction or implementation work;
4. consume concise summaries and evidence references;
5. persist progress/dependencies;
6. select the next delta.

Broad repository archaeology in the parent context defeats the purpose of externalized state and recreates context dilution.

## Relationship to reconciliation reasoning

Reconciliation reasoning remains:

```text
J = f(N_scope, O_scope, X)
```

The authoritative recovery boundary defines where `N` and known `O` come from after session loss. `X` remains agent-expandable, but expansion is for judging or validating a bounded delta, not for rediscovering which work exists or what state MangoMe already records.

## Operational language is part of recovery hygiene

A recovered coordinator must not silently change the human working language. `recovery_context` exposes a language policy requiring human-visible recovery/control-plane narration to inherit the current user/session language. Persona, memory, model defaults, or imported prompts do not override that rule.

Canonical field names, state values, protocol identifiers, and reason codes remain stable machine tokens. Only the surrounding human explanation is localized.


## Three-state native restore

`session_restore` is read-only with respect to Project/Family/Specification identity and returns `STATE_FOUND`, `STATE_PARTIAL`, or `STATE_NOT_FOUND`. Missing state is never replaced by creating new work and calling it restored. `STATE_PARTIAL` permits bounded validation/backfill only; productive work requires canonical `next_executable_items`. An ACTIVE goal/project/family is unfinished intent, not execution permission.
