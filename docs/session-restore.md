# Native session restore

MangoMe restores durable work state before productive execution. In managed v0.3.3 clients this read-only snapshot is populated automatically when MangoMe initializes; the worker does not need to call restore merely because a session started.

```text
RECOVERY / STATUS REQUEST OR UNMANAGED HOST
  ↓
session_restore / session_bootstrap
  ├─ STATE_FOUND   → canonical next_executable_items / pending assurance work
  ├─ STATE_PARTIAL → bounded validation/backfill only
  └─ STATE_NOT_FOUND → preserve the absence; do not synthesize Project/Family/Spec state
```

`STATE_NOT_FOUND` is evidence of a bootstrap/persistence gap, not permission to create replacement state and call it recovered. Genuine new work uses `enter_work`; historical import/backfill remains explicit and distinguishable from restore.

Execution permission is derived from canonical executable items and dependencies. Unfinished intent, an ACTIVE goal/project/family, or a user saying “continue” cannot silently bypass BLOCKED dependencies.


For ordinary managed assignments, the preferred worker-facing path is:

```text
local understanding / tentative decomposition
    ↓
reconcile_assignment
    ↓
canonical restore state + disposition
    ↓
current-turn binding / governed productive effect
```

This preserves authoritative recovery semantics without forcing restore-first cognition.
