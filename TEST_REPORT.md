# Test Report — MangoMe v0.3.9

Date: 2026-09-28

Baseline: public `tonnestate/MangoMe` `main` at v0.3.8 (`ead3a42b1b88787355ea3b3d913407c49e30254f`), extended by the v0.3.9 observation-routing / Codex-integration hardening in this delta.

## Local deterministic suite

Command:

```bash
PYTHONPATH=src make check
```

Result:

```text
171 passed, 3 skipped in 2.05s
compileall PASS
required release surfaces PASS
canonical/package Agent Skill byte-identity PASS
```

Skipped checks:

- MCP in-process surface integration: the `mcp` dependency is not installed in this packaging interpreter.
- Two real MongoDB integration checks: `MANGOME_TEST_MONGO_URI` is not configured in this packaging environment.

These skips are not PASS claims. CI/runtime verification remains responsible for those environment-dependent paths.

## Packaging check

A wheel was built without dependency resolution/build isolation:

```bash
python -m pip wheel --no-deps --no-build-isolation .
```

Result:

```text
mangome_mcp-0.3.9-py3-none-any.whl built successfully
packaged mangome/skill/SKILL.md present
```

## v0.3.9 regression scope

The deterministic suite now covers, in addition to the prior governance/assurance tests:

- Codex MCP + Skill are user-scoped and do not depend on project catalog/trust state.
- A tiny user-level Codex `AGENTS.md` trigger is idempotent and workspace MangoMe blocks are removed without deleting unrelated project instructions.
- The Codex activation rule explicitly loads the installed MangoMe Skill before MangoMe work, so a present-but-not-selected Skill cannot silently fall back to generic routing.
- Legacy `mangome_eval` does not satisfy exact managed-server attestation.
- A visible-but-unconfirmed MCP is not treated as connected.
- Explicit workspace arguments override stale process-global read-only bindings.
- Child/broad cwd rebinding succeeds only for one compatible canonical workspace and fails closed when ambiguous.
- Legacy persisted filesystem roots can act as compatibility aliases only when their deterministic workspace Project already exists.
- Pure Big-Bang discovery does not persist Artifact rows.
- Big-Bang advisory reconciliation remains mutation-free.
- Explicit discovery defaults to bounded output and no Git scan.
- Large direct candidate reconciliation is guarded in favor of server-side `reconcile_bigbang_scan`.
- Big-Bang reading skips symlinks and private credential/agent/cache/build trees and streams file hashes instead of loading whole files into memory.
- Big-Bang traversal itself is bounded by file/depth limits and prunes excluded directories before descent.
- The Agent Skill routes observation-only commands around IntakeGov / assignment reconciliation / restore / admission and prevents duplicate discovery.
- `filesystem_inventory` is the pure observation surface while `filesystem_scan` remains the explicit persistent inventory path.
- MCP version comes from package `__version__` rather than a separate hard-coded literal.
- `RUNTIME_PROFILE_REQUIRED` is explicitly scoped to external dispatch/capability-sensitive host decisions and reports that ordinary local work is not blocked.

## Live acceptance gates after upload

The following should be checked on the actual host because they require Codex/MCP/MongoDB integration:

```text
1. New Codex session sees exact MCP server `mangome`, not `mangome_eval`.
2. `health` reports v0.3.9 and the intended database binding (`mangome`).
3. `$mangome` is discoverable and the global trigger causes the Skill to be invoked when MangoMe is relevant.
4. `discover /root/contracts` performs one `bigbang_scan` only, returns the bounded summary, and stops without IntakeGov/reconcile/restore/reconcile_bigbang.
5. The discovery does not add canonical Artifact rows.
6. A persisted canonical workspace is resolved from the active cwd without `STATE_NOT_FOUND`; multiple candidates return `WORKSPACE_BINDING_AMBIGUOUS`.
```
