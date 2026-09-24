# MangoMe Agent Skill

MangoMe is the canonical work-state system for durable multi-agent projects.

## Non-negotiable rules

1. **Read first.** Every agent may and should read all relevant MangoMe project state before acting.
2. **Categorize every assignment.** Call `intake_request`; use IntakeGov's classification when available.
3. **Resolve before creating.** Search existing family/contract/slice identity before creating a new family.
4. **A prompt is not a contract.** Register a contract only when a durable contract contribution exists or the current workflow explicitly creates one.
5. **Spec before execution.** Ensure the family has the specification that defines objective, deliverables, constraints, acceptance criteria and evidence expectations.
6. **Plan before mutate.** Submit a plan with intended slices, estimate, scope and expected artifacts before productive work.
7. **Preserve existing slices.** If the contract already has phases/slices/workstreams, import/reuse them. Do not replace them merely because you prefer another decomposition.
8. **Collision warnings never block.** Observe them, expect concurrent changes, re-read affected artifacts when needed, then continue.
9. **Persist state during meaningful progress.** Update current step, total steps, blocker and evidence. Do not rely on chat/session memory.
10. **DONE is a claim.** Use `claim_done`; never describe the slice as VERIFIED unless MangoMe assurance says VERIFIED/ACCEPTED.
11. **Gate PASS requires evidence.** Persist the evidence first, then reference its evidence ID when setting PASS.
12. **WAIVED requires approval.** Never waive a gate without an APPROVED `WAIVE_GATE` record for `<slice_id>:<gate_id>`.
13. **No self-verification.** The actor that last executed the slice may not verify its own DONE claim.
14. **ACCEPTED is explicit.** Owner/human acceptance is separate from verification and requires an approved `ACCEPT_SLICE` decision.
15. **Close plans that are no longer active.** Use `close_plan` so stale plans do not continue to create collision traffic.
16. **Do not invent missing truth.** Use UNKNOWN/UNRESOLVED or attach a suggested relation when evidence is insufficient.

## Start of work

For every executable assignment:

```text
intake_request
→ resolve
→ read_context
→ verify/create specification
→ submit_plan
→ inspect collision warning
→ start_slice
```

The plan must state what you intend to do, which slices you will touch/create, expected artifacts/scope, acceptance expectations, and an estimate when meaningful.

## Existing contract handoff

When a user hands you an existing contract plus existing slices, use `import_contract_bundle` or equivalent explicit onboarding. Preserve the supplied slice identities and states. Then create an intake request/spec/plan for the new execution session.

## During work

Use `update_slice_progress` whenever the durable project position changes materially. Attach evidence with `submit_evidence`. Register durable artifacts with `attach_artifact`. Use `link_entities` for explicit relations such as `ADDS_TO`, `AMENDS`, `EXTENDS`, `REPAIRS`, `RECOVERS`, `SUPERSEDES`, or `RELATES_TO`.

New work discovered during execution should become an additional slice or contract contribution without rewriting history.

## Completion and verification

When implementation work is finished:

```text
claim_done
```

This produces `DONE_CLAIMED / UNVERIFIED` unless assurance already exists.

For a PASS gate:

```text
submit_evidence
→ set_gate_controlled(status=PASS, evidence_ids=[...])
```

For a gate that must be waived:

```text
request_override(action_type=WAIVE_GATE, subject_id=<slice_id>:<gate_id>)
→ explicit approval
→ set_gate_controlled(status=WAIVED, approval_id=...)
```

Verification is a separate action by a different actor:

```text
verify_slice
```

After verification, owner/human acceptance may be recorded explicitly:

```text
request_override(action_type=ACCEPT_SLICE, subject_id=<slice_id>)
→ explicit approval
→ accept_slice
```

## Approval trust boundary

MangoMe records and enforces approval-state relationships, but v0.1.1 does not authenticate MCP caller identities. `actor_id`, `decided_by`, and related identity strings come from the host environment. Do not represent this as cryptographic authorization.

## Session loss / context loss

Do not reconstruct project truth from your own memory. Read MangoMe again. The persistent fields `last_started_slice_id`, `active_slice_ids`, `last_done_claimed_slice_id`, `last_verified_slice_id`, current steps, gates and timestamps are authoritative state inputs for the next plan.

MangoMe stores state; it does not force an automatic recovery/replay strategy. Decide the next plan from the observed state and current artifacts.

## Parallel work

Collision warnings are advisory. Never use a collision warning as a reason for inactivity. Re-read overlapping artifacts when appropriate and continue with greater care. Close obsolete plans to reduce stale warnings.

## Model/cost receipt

When execution telemetry is available, register the model identity and write an execution receipt. Include context size, tokens, execution/verification/repair/human costs and final outcome. This data is evidence for future routing, not a popularity score.

## Big-Bang import

`bigbang_scan` is non-destructive discovery. `CONTRACT_CANDIDATE` is not a canonical contract. Ambiguous relationships stay unresolved/suggested until there is evidence or authorized confirmation.

## External model reconciliation

An external ChatGPT/Claude/Gemini review is advisory. Import its result as evidence/suggestion. Never let an external reviewer directly rewrite canonical MangoMe state.
