# MangoMe v0.1.1 — Integrity & operability

v0.1.1 closes the most important gaps in the first executable baseline without redesigning the v0.1 domain model.

## Verification chain

`DONE_CLAIMED` remains a stable execution state. It does not imply verification.

For a gate to become `PASS`, at least one persisted evidence record for the same slice is required. A failing evidence result cannot support `PASS`.

A `WAIVED` gate requires an explicit approved `WAIVE_GATE` approval whose subject is exactly:

```text
<slice_id>:<gate_id>
```

The actor that last executed the slice may not verify its own `DONE_CLAIMED` state. This is a domain invariant, not an authentication mechanism.

## Human acceptance

`VERIFIED` and `ACCEPTED` are separate. `ACCEPTED` requires an approved `ACCEPT_SLICE` approval for that slice.

Approval records can carry a `decision_ref` pointing to the human decision source.

## Important trust boundary

MangoMe v0.1.1 still does not authenticate MCP callers. `actor_id`, `decided_by`, and `accepted_by` are declarative identities supplied by the host. Production-grade identity/authentication belongs at the MCP transport/runtime boundary and is a later hardening step.

## Added MCP tools

- `attach_artifact`
- `link_entities`
- `close_plan`
- `request_override`
- `approve_override`
- `reject_override`
- `list_approvals`
- `set_gate_controlled`
- `accept_slice`

The original v0.1 tools remain available. Because the runtime now uses `IntegrityMangoMeService`, the existing `set_gate` and `verify_slice` tools also inherit the new integrity checks.

## CI

The GitHub Actions workflow runs the existing tests, the new integrity tests, a real MongoDB integration test against a MongoDB 7 service container, an MCP import smoke test, and a skill-mirror consistency check.
