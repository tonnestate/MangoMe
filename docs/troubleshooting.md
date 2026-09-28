# MangoMe Troubleshooting

This guide is for operators and developers who need to diagnose common MangoMe failures without reconstructing state from old agent memory or randomly changing the host.

Start with deterministic checks.

## First three checks

Run:

```bash
mangome health
mangome doctor
mangome attest-client codex
```

or, for Claude Code:

```bash
mangome attest-client claude-code
```

Do not begin by searching historical agent memory, old contract folders, cached summaries, or unrelated repositories.

## Quick reference

| Code / symptom | Meaning | First action |
|---|---|---|
| `WRONG_MANGOME_DATABASE` | Runtime database differs from the managed expected database | Check `MANGOME_DATABASE` and `MANGOME_EXPECTED_DATABASE` |
| `DATABASE_UNREACHABLE` | MongoDB cannot be reached within the configured timeout | Check MongoDB service, URI, socket, and permissions |
| `LEGACY_EVAL_DATABASE_REQUIRES_OPT_IN` | Runtime is pointed at a legacy eval database | Bind ordinary work to `mangome` |
| `STATE_NOT_FOUND` | No canonical recoverable work state was found | Determine whether this is genuinely new work or a binding problem |
| `WORKSPACE_BINDING_AMBIGUOUS` | More than one canonical workspace could match | Select/fix the intended workspace explicitly |
| `SKILL_NOT_INSTALLED` | Managed Skill file is missing | Re-run setup/doctor repair |
| `SKILL_VERSION_MISMATCH` | Installed Skill differs from the current MangoMe package/source | Re-run setup/doctor repair |
| `MCP_NOT_VISIBLE` | Client does not expose the managed MangoMe MCP server | Inspect client config and stale/shadow bindings |
| `WRONG_MANGOME_VERSION` | Running MCP version differs from the managed expected version | Restart/rebind the client to the intended runtime |
| `WRONG_MCP_TARGET` | Managed client points at the wrong Python/source/cwd/env | Re-run managed setup/doctor repair |
| `CONFIGURATION_SHADOWING` | More than one MangoMe-like client binding may be active | Remove or repair stale MangoMe bindings |
| `RUNTIME_PROFILE_REQUIRED` | No host-observed runtime profile exists for a delegation/capability check | Publish via the trusted router/host only if this is actually delegated work |
| `ROUTER_CAPABILITY_REQUIRED` | A worker tried to publish runtime state without router authority | Fix host/orchestrator integration; do not let the worker self-promote |
| `CURRENT_RUNTIME_CAPABILITY_MISSING` | Delegated worker lacks a required current capability | Checkpoint and hand off only the missing capability |
| `PROJECT_MCP_APPROVAL_REQUIRED` | Claude project-scope MCP awaits client trust approval | Approve through the client or use local scope |
| `CLIENT_CONFIGURATION_AMBIGUOUS` | Managed config cannot be parsed safely | Inspect the named config file; do not let MangoMe guess |

## `STATE_NOT_FOUND`

`STATE_NOT_FOUND` means MangoMe did not find a canonical recoverable state for the resolved project/workspace identity.

It does **not** mean:

- "search the whole filesystem";
- "read old agent memory";
- "create replacement Project/Family/Specification state";
- "assume the database is empty";
- "assume this is a new task".

Check:

```bash
mangome health
```

Confirm:

```text
database_binding.database = mangome
database_binding.state = BOUND
```

Then verify the workspace/client binding with:

```bash
mangome doctor
```

For genuinely new work, new admission is valid. For historical/resume work, missing state must remain missing until an explicit recovery/backfill path is chosen.

## `WRONG_MANGOME_DATABASE`

MangoMe treats database identity as deployment state.

Normal local production:

```text
MANGOME_DATABASE=mangome
```

Do not silently fall back to:

```text
mangome_uai_eval
```

Check:

```bash
mangome health
```

If the client still launches a stale binding, run:

```bash
mangome doctor --repair
```

Then restart the client/MCP runtime.

## `DATABASE_UNREACHABLE`

Check:

- MongoDB is running;
- the configured URI is correct;
- the expected socket/port is listening;
- the MangoMe service identity has permission;
- the credential source is correct;
- the host is not using a stale client config.

MangoMe uses bounded MongoDB connection/server-selection timeouts so an unreachable database should fail quickly rather than hang for minutes.

## `WORKSPACE_BINDING_AMBIGUOUS`

MangoMe can read-only rebind from a broad or child cwd to an existing canonical workspace only when the match is unambiguous.

If several canonical workspaces match, MangoMe returns:

```text
STATE_PARTIAL
WORKSPACE_BINDING_AMBIGUOUS
```

That is intentional.

Do not make MangoMe guess.

Bind the client to the intended workspace explicitly.

## Skill problems

### `SKILL_NOT_INSTALLED`

For managed Codex setup, the expected user-scoped Skill location is:

```text
~/.codex/skills/mangome/SKILL.md
```

For Claude Code, managed setup uses its supported Skill integration.

Repair:

```bash
mangome doctor --repair
```

### `SKILL_VERSION_MISMATCH`

The installed Skill differs from the canonical Skill packaged with the current MangoMe runtime.

Repair:

```bash
mangome setup --client auto
```

or:

```bash
mangome doctor --repair
```

Then restart the client so the new managed instructions are effective.

### Skill file exists, but behavior still looks wrong

A file existing on disk is not proof that the running agent has consumed its contents.

Check:

- managed instructions are present;
- the client is running the intended MangoMe version;
- stale user/project instructions are not shadowing the managed configuration;
- the current session was restarted after configuration changes.

## `MCP_NOT_VISIBLE`

Run:

```bash
mangome attest-client codex
```

or:

```bash
mangome attest-client claude-code
```

Then:

```bash
mangome doctor
```

Common causes:

- stale client config;
- wrong project/user scope;
- old MangoMe MCP alias;
- old Python environment;
- current client session started before setup changed.

## `WRONG_MANGOME_VERSION`

A long-lived client can continue talking to an older MCP process even after the repository has been updated.

The repository version and running process version are different facts.

Run:

```bash
mangome health
```

and compare the reported runtime version with the intended release.

Then repair/restart the managed client binding.

## `RUNTIME_PROFILE_REQUIRED`

This code belongs to runtime eligibility/delegation governance.

It is appropriate when an external orchestrator asks whether a named worker is eligible for a bounded delegated task.

It should **not** block ordinary local work.

If it appears during a normal local read/edit/test flow:

1. confirm the running MangoMe version is current;
2. restart the client after upgrade;
3. verify that the agent is not incorrectly calling `execution_eligibility` for its own normal local work;
4. check for stale Skill/instructions.

A worker must not fix this by self-calling `publish_worker_runtime`. That operation is router/host privileged by design.

## Discovery loops or huge permission prompts

For:

```text
discover PATH
```

expected behavior is:

```text
one bounded scan
→ candidate results
→ STOP
```

A discovery-only request should not automatically run:

```text
intake_request
reconcile_assignment
session_restore
reconcile_bigbang
enter_work
```

and should not resend hundreds of candidate records as a second giant tool payload.

If it does, verify that the client is actually running the current MangoMe Skill/runtime.

For CLI discovery:

```bash
mangome scan /path/to/source --no-git
```

Use Git discovery only when it is actually required.

## Avoid these recovery anti-patterns

Do not "fix" MangoMe by:

- searching old `.claude` / `.codex` memory for current authority;
- switching databases until state appears;
- creating new canonical work and calling it restored;
- broadly scanning the host because restore failed;
- letting an agent invent router/controller credentials;
- disabling trust boundaries to make an error disappear;
- treating `DONE_CLAIMED` as `VERIFIED`;
- modifying DNS/firewall/resolver/SSH as part of ordinary MangoMe setup.

## When to use `doctor --repair`

Use:

```bash
mangome doctor --repair
```

for supported MangoMe-managed client configuration drift.

Do not use it as a substitute for:

- database migration authorization;
- host networking repair;
- MongoDB administrative repair;
- arbitrary filesystem cleanup;
- unrelated application configuration.

## Still stuck?

Capture these four outputs:

```bash
mangome health
mangome doctor
mangome attest-client codex
python -c "import mangome; print(mangome.__version__)"
```

For Claude Code, replace the Codex attestation command accordingly.

Those outputs usually separate:

```text
runtime problem
database problem
workspace problem
client binding problem
Skill/instruction problem
```

without requiring repository archaeology.
