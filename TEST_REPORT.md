# Test Report — MangoMe v0.1.9rc4

Date: 2026-09-26

Canonical baseline: public `tonnestate/MangoMe` `main` at v0.1.9rc3 (`bc75d59fe5ad1797fad3e8e4ebc5e56f27e5db93`), extended by the rc4 changes in this package. Required release dotfile surfaces are included in the package and checked for internal consistency.

## Local deterministic suite

Command:

```bash
make check
```

Result in the packaging environment:

```text
90 passed, 3 skipped in 1.40s
compileall PASS
required release surfaces PASS
four Agent Skill surfaces byte-identical PASS
```

Skipped checks:

- MCP in-process surface integration: the `mcp` dependency is not installed in this sandbox interpreter.
- Two real MongoDB integration checks: `MANGOME_TEST_MONGO_URI` is not configured in this sandbox.

These are environment skips, not PASS claims. Post-upload CI remains responsible for MCP and real MongoDB verification.

## rc4 regression scope

The deterministic suite now covers the new observed failure classes in addition to the prior assurance/recovery tests:

- `STATE_NOT_FOUND` restore does not create replacement Project/Family/Specification state;
- BLOCKED existing work can be restored while `productive_execution_allowed` remains false and `next_executable_items` remains empty;
- portable multi-root discovery accepts host/user-independent typed scopes;
- nested/scattered Git checkout locations can be observed without turning them into canonical project truth;
- agent-private `.claude` context is excluded from filesystem truth inventory;
- discovered generic documents are stored as references/metadata rather than copied file bodies;
- high-cost fan-out no longer has the rc3 one-active-per-family serialization rule: multiple separately Owner-authorized tasks may coexist, while task-scoped authorization and runtime parallelism remain enforced.

## Release-candidate behavior

v0.1.9rc4 adds native three-state session restore (`STATE_FOUND`, `STATE_PARTIAL`, `STATE_NOT_FOUND`), restore-before-execution semantics, portable typed discovery scopes, physical repository-location observations, and a provider-neutral infrastructure boundary.

Important boundaries remain explicit:

- MangoMe does not invent missing recovery state.
- Genuine NEW work through `enter_work` is distinct from historical import/backfill and from native restore.
- ACTIVE intent/goal/project state is not execution permission.
- `DONE_CLAIMED` remains distinct from `VERIFIED` and `ACCEPTED`.
- MangoMe source is infrastructure and must not be modified by agents unless their explicit assignment targets MangoMe itself; hard filesystem enforcement belongs to the host/runtime.
- Generic Git/filesystem/DMS document bodies remain in their source systems; MangoMe persists bounded metadata, hashes, references, relations and explicitly admitted semantic state.
- Model dispatch is external. MangoMe exposes eligibility/authorization/checkpoints; the host/orchestrator must enforce those decisions at the real dispatch boundary.

## CI gate after upload

Post-upload CI should run the Python 3.10/3.11/3.12 matrix, MongoDB 7 integration checks without skips, MCP surface tests including `session_restore`/`session_bootstrap`, UAI round-trip, source compilation, and byte-identity checks for all Agent Skill surfaces.
