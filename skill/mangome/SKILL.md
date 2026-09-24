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
11. **Do not delete gates.** If a gate is wrong, request an explicit approved change; do not silently remove requirements.
12. **Do not invent missing truth.** Use UNKNOWN/UNRESOLVED or attach a suggested relation when evidence is insufficient.

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

Use `update_slice_progress` whenever the durable project position changes materially. Attach evidence with `submit_evidence`. New work discovered during execution should become an additional slice or contract contribution without rewriting history.

## Completion

When implementation work is finished:

```text
claim_done
```

This produces `DONE_CLAIMED / UNVERIFIED` unless assurance already exists.

Acceptance gates must be recorded with `set_gate`. Only use `verify_slice` when all required gates are PASS or explicitly WAIVED through the authorized process.

## Session loss / context loss

Do not reconstruct project truth from your own memory. Read MangoMe again. The persistent fields `last_started_slice_id`, `active_slice_ids`, `last_done_claimed_slice_id`, `last_verified_slice_id`, current steps, gates and timestamps are authoritative state inputs for the next plan.

MangoMe stores state; it does not force an automatic recovery/replay strategy. Decide the next plan from the observed state and current artifacts.

## Model/cost receipt

When execution telemetry is available, register the model identity and write an execution receipt. Include context size, tokens, execution/verification/repair/human costs and final outcome. This data is evidence for future routing, not a popularity score.

## Big-Bang import

`bigbang_scan` is non-destructive discovery. `CONTRACT_CANDIDATE` is not a canonical contract. Ambiguous relationships stay unresolved/suggested until there is evidence or authorized confirmation.

## External model reconciliation

An external ChatGPT/Claude/Gemini review is advisory. Import its result as evidence/suggestion. Never let an external reviewer directly rewrite canonical MangoMe state.
