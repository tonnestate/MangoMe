# Zero-touch operability — MangoMe v0.1.8

MangoMe's governance vocabulary is an implementation detail. A user should be able to open a supported coding client, describe normal work, and receive governed project behavior without being expected to understand Big-Bang discovery, contract families, slices, plans, evidence classes, or verification commands.

v0.1.8 therefore adds a thin operability layer around the existing truth model. It does not create a second state model and does not weaken the existing assurance path.

## Managed setup

The installer/operator can configure supported local clients with:

```bash
mangome setup --client auto
```

or explicitly:

```bash
mangome setup --client claude-code --client codex
```

Managed configuration binds the client to the current MangoMe Python runtime, selects the WORKER role, records the expected MangoMe version, and enables automatic workspace attachment. MongoDB connection secrets are not written into generated client configuration; the server continues to obtain sensitive connection material from the surrounding runtime environment.

Claude Code setup also installs the current MangoMe Agent Skill at the supported project Skill location **and** a short always-on project rule at `.claude/rules/mangome.md`. The rule exists because Skills are contextual/on-demand; zero-touch behavior must not depend on a user explicitly invoking a Skill.

Codex setup writes the project MCP binding in `.codex/config.toml` and adds a bounded MangoMe managed block to the repository `AGENTS.md`. Existing instructions are preserved. Codex loads repository `AGENTS.md` instructions automatically, so the user does not need to request MangoMe explicitly.

These always-on instructions are intentionally short: they tell the client to establish `workspace_status` for substantive work and to use MangoMe internally, without copying the whole MangoMe Skill into every prompt.

## Automatic workspace attachment

When a managed MCP server starts with `MANGOME_AUTO_ATTACH=1`, MangoMe resolves the configured workspace root (or the current Git/work directory when explicitly refreshed) and performs:

```text
unknown workspace
    → deterministic filesystem inventory
    → one non-destructive Big-Bang discovery pass
    → advisory reconciliation

known workspace
    → deterministic filesystem inventory refresh
```

Big-Bang discovery is no longer a normal user command. `bigbang_scan` remains available for diagnostics and explicit maintenance.

Automatic discovery does not admit contracts, specifications, slices, or assurance claims merely because matching text exists on disk. Ambiguity remains unresolved until the normal canonicalization path has enough authority/evidence.

## Client attestation and drift repair

Use:

```bash
mangome attest-client claude-code
mangome attest-client codex
mangome doctor
mangome doctor --repair
```

The operability layer checks the managed MCP command, MangoMe version expectation, workspace binding, runtime role, backend/database name, the expected always-on client instruction, and the Claude Code Skill mirror. Where the client CLI is installed it also asks the client to list its MCP servers and confirms that MangoMe is visible.

Managed files are backed up once before MangoMe changes them. Stale MCP entries explicitly named for MangoMe are treated as managed/legacy drift and can be removed during setup so an old launcher does not remain active in parallel. MangoMe does not silently rewrite unrelated or semantically ambiguous third-party configuration; ambiguous shadowing remains a fail-closed readiness result.

## Runtime identity check

Managed client configuration carries `MANGOME_EXPECTED_VERSION`. A v0.1.8 runtime compares that value with the package it actually loaded before creating the backing-store service. A mismatch fails closed.

Source-root identity can also be carried when setup is executed from a Git-backed editable installation. This prevents a client that was intentionally bound to one source checkout from silently executing a different checkout with the same command surface.

## Agent behavior

The MangoMe Skill and MCP initialization instructions make the user-facing rule explicit:

> Ordinary user intent is sufficient. Never require the user to invoke Big Bang, create a Slice, or call `begin_work` manually.

The worker still has to respect MangoMe's domain invariants internally:

```text
read / resolve
→ specification
→ plan-before-mutate
→ execution
→ DONE_CLAIMED
→ independent verification
→ optional authorized acceptance
```

The simplification is in the interface, not in the durable truth model.

## Boundaries

v0.1.8 does not claim to be a universal package manager or client policy engine. It currently supports managed local configuration for Claude Code and Codex. It does not:

- silently overwrite ambiguous global/managed organization configuration;
- create credentials;
- grant verifier/owner capability to worker clients;
- scan every filesystem root on a host;
- convert discovery candidates into semantic truth;
- bypass client trust/approval mechanisms;
- prove that a client actually used every MangoMe tool correctly merely because registration succeeded.

Those boundaries are deliberate. Safe deterministic operability drift should self-heal; genuine authority or semantic ambiguity should not.
