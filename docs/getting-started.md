# Getting Started with MangoMe

This guide takes a new user from a fresh checkout to a working MangoMe installation with Codex or Claude Code.

It assumes no prior knowledge of MangoMe internals.

## 1. Clone and install

From the repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Confirm the CLI is available:

```bash
mangome --help
```

## 2. Configure persistence

### Recommended local production setup

MangoMe uses MongoDB as its canonical production store.

```bash
export MANGOME_BACKEND=mongo
export MANGOME_MONGODB_URI='mongodb://127.0.0.1:27017'
export MANGOME_DATABASE='mangome'
```

The ordinary local production database is:

```text
mangome
```

`mangome_uai_eval` is a legacy/evaluation database and is not a normal production fallback.

### Deterministic in-memory mode

For isolated tests:

```bash
export MANGOME_BACKEND=memory
```

Do not use the in-memory backend when you expect state to survive process restarts.

## 3. Configure your agent client

Run:

```bash
mangome setup --client auto
```

Or configure clients explicitly:

```bash
mangome setup --client codex
mangome setup --client claude-code
```

### Codex

Managed setup configures the MangoMe MCP binding and installs the MangoMe Agent Skill in the user-scoped Codex Skill location:

```text
~/.codex/skills/mangome/SKILL.md
```

The Skill file being present is not itself a verification that a running model has already consumed its contents. Managed instructions provide the host-side trigger so MangoMe use does not depend only on heuristic Skill selection.

### Claude Code

The default is private local scope:

```bash
mangome setup --client claude-code
```

Project scope is explicit:

```bash
mangome setup --client claude-code --claude-scope project
```

Project scope may require Claude Code's own trust approval.

## 4. Verify runtime health

Run:

```bash
mangome health
```

The important normal state is:

```text
process_ready: true
database_ready: true
database_binding:
  database: mangome
  state: BOUND
```

A healthy MCP process with the wrong database is **not** a healthy MangoMe deployment.

## 5. Verify client binding

For Codex:

```bash
mangome attest-client codex
```

For Claude Code:

```bash
mangome attest-client claude-code
```

General check:

```bash
mangome doctor
```

Safe managed repair:

```bash
mangome doctor --repair
```

`doctor --repair` manages MangoMe's documented client/workspace integration surfaces. It is not a general host repair tool and should not modify DNS, firewall, SSH, resolver, package-manager, or unrelated system configuration.

## 6. Understand the three common workflows

### A. New work

Example user request:

```text
Review this service, fix the failing behavior, and add regression tests.
```

Conceptually:

```text
understand locally
    ↓
reconcile before productive effect
    ↓
no existing work → admit genuine new work
    ↓
execute
    ↓
persist progress/evidence
    ↓
DONE_CLAIMED
    ↓
independent verification when required
```

The user does not need to create MangoMe objects manually.

### B. Resume existing work

Example:

```text
Continue the work from yesterday.
```

Conceptually:

```text
current user intent
    ↓
canonical MangoMe recovery
    ↓
existing durable WorkIdentity
    ↓
unfinished delta
    ↓
continue bounded work
```

Recovery must not be replaced by broad repository archaeology or remembered agent prose.

### C. Discovery only

Example:

```text
discover /root/contracts
```

Expected behavior:

```text
bounded scan
    ↓
candidate results
    ↓
return results
    ↓
STOP
```

Discovery is observation only.

It does **not** automatically mean:

```text
intake
restore
reconcile assignment
reconcile every candidate
create work
admit canonical truth
```

If you later want to import or reconcile discovered material, request that as a separate action.

## 7. Basic CLI commands

Health:

```bash
mangome health
```

Client diagnostics:

```bash
mangome doctor
mangome attest-client codex
mangome attest-client claude-code
```

Explicit discovery:

```bash
mangome scan /path/to/source --no-git
```

Resolve known identity:

```bash
mangome resolve SOME-ID
```

Project overview:

```bash
mangome project PROJECT-REF
```

Family status:

```bash
mangome status FAMILY-ID
```

Non-destructive maintenance diagnostics:

```bash
mangome diagnose
```

Schema migration inspection:

```bash
mangome migrate
```

Applying a migration is a separate explicit action:

```bash
mangome migrate --apply
```

Do not run schema mutation merely because a runtime or client is misconfigured.

## 8. What `DONE` means

MangoMe separates execution from assurance.

```text
worker says done
    ↓
DONE_CLAIMED
    ↓
independent evidence / verification
    ↓
VERIFIED
    ↓
optional owner acceptance
    ↓
ACCEPTED
```

This distinction is intentional.

A worker completing its implementation does not automatically prove that the implementation is correct.

## 9. Runtime profiles and delegation

A normal local worker does **not** need to publish a runtime profile merely to read, reason, edit, test, or continue ordinary local work.

Runtime profiles belong to delegation and capability-sensitive external orchestration.

If you see:

```text
RUNTIME_PROFILE_REQUIRED
```

during ordinary local work, that usually indicates a stale runtime/client, an incorrect integration path, or delegation governance leaking into the normal worker path.

See [troubleshooting.md](troubleshooting.md).

## 10. Next reading

- [Start Here](START_HERE.md)
- [Troubleshooting](troubleshooting.md)
- [Why MangoMe](WHY_MANGOME.md)
- [Assignment Reconciliation](assignment-reconciliation.md)
- [Authoritative Recovery](authoritative-recovery.md)
- [Big-Bang Import](bigbang-import.md)
- [Delegation Governance](delegation-governance.md)

You can use MangoMe productively without learning every advanced protocol first.
