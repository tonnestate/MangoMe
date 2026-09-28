# RAE/1 — Reconcile Assignment Before Effect

MangoMe v0.3.3 introduces a worker-facing assignment bridge for ordinary managed work.

## Principle

```text
THINK FREELY. RECONCILE BEFORE EFFECT.
```

A worker may read, search, inspect, reason, classify, form hypotheses and draft a tentative decomposition without first loading MangoMe state. Those activities remain worker judgment. Before the first durable/productive effect, the assignment must be reconciled with MangoMe.

## `reconcile_assignment`

`reconcile_assignment(request_text, workspace_root=None)` is read-only with respect to canonical work identity and normative truth. It resolves the managed workspace and canonical restore state and returns a disposition:

- `RECONCILE_WITH_EXISTING_WORK` — map the worker's tentative understanding onto existing WorkIdentity, normative baseline and unfinished work; bind the current user turn before productive effect.
- `BOUNDED_RECOVERY_REQUIRED` — resolve partial canonical state through bounded recovery/backfill; productive mutation remains blocked.
- `NEW_OR_UNADMITTED_WORK` — genuinely new work may be admitted with `enter_work`; historical/resume work must use explicit import/backfill.

The call never canonicalizes the prompt or tentative decomposition.

## Observation-only operations

RAE/1 is an effect-boundary bridge for productive assignments, not a mandatory preflight for every MCP call. Read-only `health`, status/show/list/resolve, explicit discovery/scan/inventory, repository/scope listing and read-only context inspection stay on their direct observation path unless the user explicitly asks to turn the result into governed work.

For example, `discover /root/contracts` means one bounded `bigbang_scan` of that path and then stop. It does not require `intake_request`, `reconcile_assignment`, restore/admission, runtime-profile eligibility, or `reconcile_bigbang`.

## Effect boundary

Productive effects include code/file/database writes, commits, deployments, external messages/actions, canonical MangoMe mutations, normative promotion and completion/verification claims.

Reading, searching, local reasoning, classification, hypotheses and tentative planning are not productive effects.

## Managed bootstrap

Managed clients use automatic read-only workspace binding. Runtime initialization does not scan or eagerly compute the canonical restore snapshot; restore is resolved lazily when reconciliation/recovery or an effect gate needs it. `MANGOME_REQUIRE_SESSION_RESTORE=1` remains a compatibility safety gate but no longer requires the worker to make a ritual restore tool call. Explicit `session_restore` remains the primitive for dedicated recovery/status workflows and unmanaged hosts.

## Invariants

```text
WorkerJudgment != Authority
TentativePlan != CanonicalPlan
STATE_FOUND != CONTINUE
STATE_NOT_FOUND != PermissionToFakeRestore
InspectionScope != MutationScope
```

The purpose of RAE/1 is to preserve model agency while governing the transition from local cognition to organizational effect.
