# Zero-touch operability — MangoMe v0.1.8.1

MangoMe's governance vocabulary is an implementation detail for the **user**, not something the runtime may ignore. v0.1.8.1 makes that boundary explicit.

The product goal is:

```text
ordinary user request
    ↓
client/runtime performs MangoMe lifecycle internally
    ↓
governed canonical work
```

It is **not**:

```text
ordinary user request
    ↓
skip planning / evidence / verification
```

## Three different kinds of truth

MangoMe keeps three sources separate.

### 1. Discovery candidates

Automatic workspace attachment, filesystem inventory and Big-Bang discovery observe files, Git metadata and identifiers. They are `CANDIDATE_ONLY` and never become canonical contract/specification history merely because they were found.

### 2. Current operational work

For an ordinary new task, the current user request relayed by the client is sufficient to create **new operational state** through `enter_work`:

```text
session_restore / session_bootstrap
    ↓
STATE_NOT_FOUND + genuinely new work
    ↓
enter_work(actor_id, request_text, ...)
    ↓
workspace Project / task-specific Family
    ↓
current-request Specification
    ↓
Request → Plan → Slice → ACTIVE
```

`enter_work` is deliberately narrow. It does not promote discovered legacy contracts, reports or audits. It only admits the current task into the normal MangoMe state machine. The Plan-before-mutate invariant remains intact.

For already admitted work, use `begin_work` or the lower-level lifecycle against the existing Family/Specification.

### 3. Assurance

Worker execution and assurance remain separate:

```text
ACTIVE
  ↓
DONE_CLAIMED
  ↓
independent AV/1 observation
  ↓
VERIFIED
  ↓
optional owner approval
  ↓
ACCEPTED
```

A worker can finish execution without possessing verifier/owner authority. `DONE_CLAIMED / UNVERIFIED` is therefore a valid durable state, not a failed workflow. A deployment that wants automatic verification must provide an isolated verifier runtime/capability channel; MangoMe does not silently grant that authority to the worker.

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

Codex setup writes the project MCP binding in `.codex/config.toml` and adds one bounded managed MangoMe block to `AGENTS.md`. Existing instructions are preserved.

## Automatic workspace attachment

With `MANGOME_AUTO_ATTACH=1`:

```text
unknown workspace
    → deterministic filesystem inventory
    → one non-destructive Big-Bang discovery pass
    → advisory reconciliation

known workspace
    → deterministic filesystem inventory refresh
```

The user is never required to request Big Bang manually. Discovery remains candidate-only in both cases.

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

v0.1.8.1 deliberately does **not** add a second lightweight/ephemeral state model. Two truth stores would make handoff and promotion semantics harder, not simpler.

The product instead keeps one governed model with two different ingress paths:

- explicit admitted existing work; and
- zero-touch admission of the current user request through `enter_work`.

Discovery remains separate until explicitly admitted. This keeps the user experience simple without weakening the canonical state machine.


## Infrastructure boundary

MangoMe is infrastructure. Agents may use it but must not modify MangoMe source/tests/configuration unless the assignment explicitly targets MangoMe. Managed hosts enable restore gating with `MANGOME_REQUIRE_SESSION_RESTORE=1`; hard filesystem enforcement remains a host responsibility.
