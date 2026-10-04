# Zero-touch operability — MangoMe v0.3.21

MangoMe's governance vocabulary is an implementation detail for the **user**, not something the runtime may ignore. v0.3.3 moves governance to the effect boundary: workers may reason freely, while productive effects must be reconciled with canonical state and authority.

The product goal is:

```text
ordinary user request
    ↓
worker may inspect / reason / form tentative decomposition
    ↓
reconcile_assignment
    ↓
client/runtime performs governed MangoMe lifecycle
    ↓
governed productive work
```

It is **not**:

```text
ordinary user request
    ↓
skip planning / evidence / verification
```

## v0.3.21 agent-proof routing and runtime generation

Zero-touch must not depend on an agent diagnosing MangoMe internals.

If the current user explicitly says a task should run without MangoMe or MangoMe is out of scope, MangoMe is not an execution dependency for that task. A MangoMe-specific failure must not be promoted into failure of otherwise executable work.

```text
FRAMEWORK_BLOCKED != TASK_BLOCKED
```

Managed startup also reconciles stale MCP generations from the same managed installation. HEALTH exposes generation drift; current and unknown processes are not treated as stale by guesswork.

```text
ONE MANAGED INSTALLATION
→ ONE ACTIVE MANGOME GENERATION
```

## v0.3.3 reconciliation-before-effect

Managed MangoMe clients already use `MANGOME_AUTO_ATTACH=1`. Runtime initialization now performs only a cheap read-only workspace binding; canonical restore is resolved lazily when reconciliation/recovery actually needs it. Therefore the worker-facing default is no longer "restore before repository exploration".

```text
THINK FREELY
    ↓
reconcile_assignment
    ↓
RECONCILE CANONICAL STATE + AUTHORITY
    ↓
PRODUCTIVE EFFECT
```

`reconcile_assignment` is read-only. It may return:

- `RECONCILE_WITH_EXISTING_WORK` for `STATE_FOUND`;
- `BOUNDED_RECOVERY_REQUIRED` for `STATE_PARTIAL`; or
- `NEW_OR_UNADMITTED_WORK` for `STATE_NOT_FOUND`.

It never promotes tentative worker judgment into canonical truth. Explicit `session_restore` remains useful for dedicated recovery/status workflows and unmanaged hosts.

## Three different kinds of truth

MangoMe keeps three sources separate.

### 1. Discovery candidates

Explicit filesystem inventory and Big-Bang discovery observe files, Git metadata and identifiers. They are `CANDIDATE_ONLY` and never become canonical contract/specification history merely because they were found.

### 2. Current operational work

For an ordinary new task, the current user request relayed by the client is sufficient to create **new operational state** through `enter_work`:

```text
tentative local understanding
    ↓
reconcile_assignment(request_text)
    ↓
STATE_NOT_FOUND + genuinely new work
    ↓
enter_work(actor_id, request_text, ...)
    ↓
workspace Project / task-specific Family / WorkIdentity
    ↓
operational-intent NormativeBaseline
    ↓
WorkTurn → Plan → Slice → ACTIVE
```

`enter_work` is deliberately narrow. It does not promote discovered legacy contracts, reports or audits. It only admits the current task into the normal MangoMe state machine. The Plan-before-mutate invariant remains intact.

For already admitted work, use `begin_work` or the lower-level lifecycle against the existing Family/Specification.

### 3. Assurance

Worker execution and assurance remain separate:

```text
ACTIVE
  ↓ worker claim
DONE_CLAIMED
  ↓ completeness validation
VALIDATED / REWORK_REQUIRED / INCONCLUSIVE
  ↓ independent AV/1 observation
VERIFIED
  ↓ all required PER/1 effects reconciled + satisfied
CLOSED
  ↓ optional owner approval
ACCEPTED
```

A worker can finish execution without possessing validator/verifier/owner authority. `DONE_CLAIMED / PENDING / UNVERIFIED / OPEN` is therefore a valid durable state, not a failed workflow. Validation is completeness judgment under a bound VERIFY/CONTROL WorkTurn; it does not create verification assurance. A deployment that wants automatic verification must provide an isolated verifier runtime/capability channel; MangoMe does not silently grant that authority to the worker. A Slice may also be `VERIFIED + OPEN` while a required PER/1 external effect remains unresolved.

Status/context surfaces expose a derived `truth_level` such as `CANONICAL_UNVERIFIED`, `CLAIMED`, `PARTIAL_VERIFIED`, `VERIFIED`, `ACCEPTED`, or `REJECTED`. This is only a projection of the existing execution/assurance state, not a second state machine.

## Managed setup

The installer/operator can configure supported local clients with:

```bash
mangome setup --client auto
```

or explicitly:

```bash
mangome setup --client claude-code --client codex
```

Managed configuration binds the client to the current MangoMe Python runtime, uses the WORKER role, records the expected MangoMe version/source root where available, and enables automatic workspace attachment.

### Claude Code

v0.1.8.1 defaults Claude Code to private **LOCAL** MCP scope for the current workspace. This avoids treating a repository-provided `.mcp.json` server as implicitly trusted. Team-shared PROJECT scope remains explicit opt-in:

```bash
mangome setup --client claude-code --claude-scope project
```

PROJECT scope may require Claude Code's own manual trust approval. MangoMe does not bypass that control.

Managed setup also installs the current MangoMe Skill under `.claude/skills/mangome/` and a short always-on rule under `.claude/rules/mangome.md`.

### Codex

Codex setup writes the portable MCP binding to `~/.codex/config.toml`, installs the Skill at `~/.codex/skills/mangome/SKILL.md`, and adds one compact trigger block to `~/.codex/AGENTS.md`. This avoids dependence on per-project trust/catalog state. Project-local MangoMe blocks are removed while unrelated project instructions/configuration are preserved.

## Automatic workspace binding and explicit observation

With `MANGOME_AUTO_ATTACH=1`, startup performs only a cheap read-only workspace binding. It does **not** inventory the filesystem, run Big-Bang discovery, inspect Git, or reconcile candidates.

```text
MCP start
    → read-only workspace binding
    → DB/runtime ready
    → STOP

explicit `discover PATH`
    → one pure `bigbang_scan([PATH])`
    → bounded candidate result
    → STOP
```

Observation-only commands are not assignments. `health`, `status`, `resolve`, `discover`/`scan`, inventory, repository-location and read-only context requests do not require IntakeGov, assignment reconciliation, restore/admission, runtime-profile checks or delegation. `reconcile_bigbang_scan` is used only when the user explicitly asks to compare discovered candidates with canonical MangoMe state.

## Client attestation and drift repair

Use:

```bash
mangome attest-client claude-code
mangome attest-client codex
mangome doctor
mangome doctor --repair
```

Static registration is not enough. For Claude Code, live attestation distinguishes an actually connected server from `Pending approval`, disconnected, failed, or merely visible/unconfirmed state. A pending project MCP server therefore cannot produce a readiness PASS.

Managed files are backed up once before deterministic changes. MangoMe removes/replaces only MangoMe-named managed/legacy bindings when the intended target is unambiguous. Unrelated or ambiguous third-party configuration remains fail-closed.

A stale runtime cannot always repair itself before it is started; this is an unavoidable bootstrap boundary. Managed current runtimes can detect identity drift through `MANGOME_EXPECTED_VERSION` and optional source-root binding, and `doctor --repair` repairs the supported local configuration.

## Runtime and capability boundary

Verifier and owner authority must remain outside ordinary worker identity. Supported options are dedicated runtime roles or runtime-injected capability tokens. Capability values must not be placed in prompts, project state, contracts, Evidence payloads, or generated client configuration.

A worker with direct MongoDB write/admin access is outside MangoMe's protection boundary. See `SECURITY.md`.

## Why there is no lightweight truth mode

v0.3.3 deliberately does **not** add a second lightweight/ephemeral state model. Two truth stores would make handoff and promotion semantics harder, not simpler.

The product instead keeps one governed model with two different ingress paths:

- explicit admitted existing work; and
- zero-touch admission of the current user request through `enter_work`.

Discovery remains separate until explicitly admitted. This keeps the user experience simple without weakening the canonical state machine.


## Infrastructure boundary

MangoMe is infrastructure. Agents may use it but must not modify MangoMe source/tests/configuration unless the assignment explicitly targets MangoMe. Managed hosts keep `MANGOME_REQUIRE_SESSION_RESTORE=1` as a compatibility gate, but managed runtime initialization now performs only a volatile read-only workspace binding. Canonical restore is lazy at reconciliation/recovery or the effect boundary. Workers are not required to invoke `session_restore` as a session-start ritual. Hard filesystem enforcement remains a host responsibility.

## v0.3 WorkIdentity / current-turn authority

`enter_work` after `STATE_NOT_FOUND` performs explicit WorkIdentity admission from the current client-relayed user request. It does not manufacture a Specification from that prompt.

Recovered ACTIVE state never grants continuation by itself. For ordinary current-user work, v0.3.20+ may bind the task-scoped EXECUTE turn from explicit current user intent. Privileged VERIFY, MODIFY, CONTROL, OWNER and ROUTER transitions keep their separate authority boundaries. A worker must not invent controller identity merely to perform ordinary user-requested work.
