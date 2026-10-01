# MangoMe v0.3.18 — Delta Web Upload

## Purpose

This delta fixes one over-strict v0.3.17 boundary discovered by the EV-U01 utility pilot.

In v0.3.17, `enter_work` required a separate host CONTROL capability whenever the
workspace already contained canonical MangoMe state. This prevented ordinary current
user intent from entering bounded executable work and caused the utility evaluation to
measure controller availability instead of MangoMe utility.

v0.3.18 changes only this ordinary-work admission path.

## Authoritative base

Apply only to the exact clean GitHub `main` base:

`1924e87d22b99acae1108391a0a8898d831531a5` — v0.3.17

GitHub remains the source of truth.

## New behavior

Explicit current user intent may enter an already-admitted workspace as bounded
ordinary work:

```text
current explicit user intent
        ↓
ENTER_WORK
        ↓
task-specific WorkIdentity
        ↓
EXECUTE WorkTurn
authorized_by = USER_INTENT_RELAYED_BY_CLIENT
```

## Security boundaries unchanged

This delta does **not** grant or weaken:

- VERIFY authority
- MODIFY / normative-truth authority
- CONTROL authority
- OWNER / ACCEPT authority
- ROUTER authority

A worker still cannot mint its own VERIFY turn.

## Package contents

- `tools/apply_v0_3_18_delta.py`
  - deterministic fail-closed patcher for the exact v0.3.17 base
  - patches:
    - `src/mangome/mcp_server.py`
    - `pyproject.toml`
    - `src/mangome/__init__.py`
    - `README.md`
    - `CHANGELOG.md`
  - installs the regression test and release notes

- `tests/test_v0318_bounded_user_intent.py`
  - proves ordinary `ENTER_WORK` works in `STATE_FOUND` without external CONTROL
  - proves the same worker still cannot self-mint VERIFY authority

- `docs/v0.3.18-release-notes.md`
  - release rationale and boundary definition

- `DELTA_MANIFEST.txt`
  - compact package manifest

## Apply

From the clean MangoMe repository root at the exact base commit:

```bash
python tools/apply_v0_3_18_delta.py
```

The patcher fails closed if:

- Git HEAD is not the exact v0.3.17 base;
- the working tree is dirty;
- expected v0.3.17 source markers are missing.

After applying, inspect the diff and run the focused regression test before committing.

## Expected version after apply

`0.3.18`

## EV-U01 consequence

After v0.3.18 is installed and the MCP process is restarted, EV-U01 may be resumed
without introducing an artificial host CONTROL runtime solely for ordinary work admission.
