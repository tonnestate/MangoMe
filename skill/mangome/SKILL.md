# MangoMe Agent Skill

MangoMe is the canonical work-state system for durable multi-agent projects.

## Non-negotiable rules

1. **Read first.** Read the relevant MangoMe project/family state before acting.
2. **Categorize every assignment.** Call `intake_request`; reuse IntakeGov classification when available.
3. **Resolve before creating.** Search existing project/family/contract/slice identity before creating a new one.
4. **A prompt is not a contract.** Register only durable contract contributions.
5. **Spec before execution.** Ensure objective, deliverables, constraints, acceptance criteria and evidence expectations are explicit.
6. **Plan before mutate.** Submit a plan before productive work.
7. **Stay bound to the plan.** After `start_slice`, every progress mutation and `claim_done` must use the same active `plan_id`.
8. **Preserve existing slices.** Import/reuse existing phases/slices/workstreams instead of casually replanning them.
9. **Collision warnings never block.** Observe traffic, re-read overlapping artifacts where useful, and continue.
10. **Persist meaningful progress.** Do not rely on chat/session memory.
11. **DONE is a claim.** `DONE_CLAIMED` is not `VERIFIED` or `ACCEPTED`.
12. **Evidence is not automatically proof.** New evidence is `UNATTESTED`; verification-grade evidence must be attested by a trusted verifier/owner capability.
13. **PASS requires attested PASS evidence.** Claims or un-attested evidence cannot satisfy a gate.
14. **WAIVED requires owner approval.** Never waive a gate without an approved `WAIVE_GATE` decision.
15. **No self-verification.** The last executing actor may not verify its own DONE claim.
16. **ACCEPTED is explicit.** Owner/human acceptance is separate from verification and requires approved `ACCEPT_SLICE` state.
17. **Close obsolete plans.** Stale plans create stale collision traffic.
18. **Do not invent missing truth.** Keep ambiguity `UNRESOLVED` / `SUGGESTED` until evidence or authorized confirmation exists.

## Start of work

```text
intake_request
→ resolve
→ read_context
→ inspect effective_family_view when contract evolution matters
→ verify/create specification
→ submit_plan
→ inspect collision warning
→ start_slice(plan_id=...)
```

The plan must state intended slices, expected scope/artifacts, acceptance expectations and an estimate when meaningful.

## Existing contract handoff

When given an existing contract and existing slices, use `import_contract_bundle` or equivalent explicit onboarding. Preserve supplied slice identity and state. Then create the current intake/spec/plan for the new execution session.

## During work

Use the same `plan_id` that started the slice:

```text
update_slice_progress(slice_id=..., actor_id=..., plan_id=...)
```

Register durable artifacts with `attach_artifact`. Use `link_entities` for explicit typed relations such as:

```text
ADDS_TO
AMENDS
EXTENDS
REPAIRS
RECOVERS
SUPERSEDES
CONFLICTS_WITH
VALIDATES
IMPLEMENTS
PART_OF
EXPOSED_BY
RELATES_TO
```

New work discovered during execution should become an additional slice or contract contribution without rewriting history.

## Completion

```text
claim_done(slice_id=..., actor_id=..., plan_id=...)
```

This produces a stable `DONE_CLAIMED / UNVERIFIED` state.

## Evidence and verification

New evidence is deliberately untrusted by default:

```text
submit_evidence(
  evidence_class=TEST_RESULT | RUNTIME_OBSERVATION | STATIC_ANALYSIS |
                 ARTIFACT_CHECK | HUMAN_ATTESTATION | EXTERNAL_REVIEW | ...
)
```

A trusted verifier or owner must attest verification-grade evidence through a runtime capability:

```text
attest_evidence
```

Then a gate may become PASS:

```text
set_gate(status=PASS, evidence_ids=[...])
```

Verification is separate and requires an independent verifier capability:

```text
verify_slice
```

Never place capability tokens in contracts, project state, evidence payloads, chat summaries or source files. Runtime/host injection is preferred.

## Owner approval

A worker may request but cannot grant approval:

```text
request_override(action_type=WAIVE_GATE | ACCEPT_SLICE, ...)
```

Owner approval/rejection requires the separate runtime approval capability. For local/self-hosted operation, a human can use the CLI so the token remains in the environment rather than the prompt:

```text
mangome approve <approval_id> --actor human-owner
mangome reject <approval_id> --actor human-owner
```

After an approved `ACCEPT_SLICE`, `accept_slice` derives the authoritative accepting actor from the approval record.

## Contract evolution

Contract contributions are append-only. Use typed relations rather than overwriting history. `effective_family_view` resolves confirmed supersession and surfaces conflicts/suggestions. It does not silently merge ambiguous prose; the current effective specification remains the operational requirements view.

## Project status

Use:

```text
status                # one family
project_overview      # all known families in a project
effective_family_view # contract evolution/current contribution set
graph                 # explicit typed relations
```

These are deterministic projections, not LLM summaries.

## Dependencies

Slices may depend on another slice at one of three levels:

```text
DONE_CLAIMED
VERIFIED
ACCEPTED
```

Do not treat an execution-level completion dependency as equivalent to an assurance-level dependency.

## Session/context loss

Do not reconstruct project truth from your own memory. Read MangoMe again. `last_started_slice_id`, active slices, last DONE claim, last verified slice, active plan binding, gates, evidence and timestamps are the durable starting point for a new plan.

MangoMe stores state; it does not replay or automatically recover a dead session.

## Big-Bang import

`bigbang_scan` is non-destructive discovery across configured filesystem roots and optional Git metadata. Identifier patterns are generic/configurable rather than hard-coded to one organization.

`reconcile_bigbang` matches discovery against canonical state without semantic mutation. Candidates, collisions and unresolved items remain explicit.

## Schema evolution and maintenance

Readers can lazily understand older schema documents. Use `migrate_schema` for an explicit dry-run or persistence migration. Use `maintenance_diagnose` for stale-plan candidates, ID collisions, open approvals and suggested relations. Diagnostics must not silently change semantic truth.

## External model reconciliation

External ChatGPT/Claude/Gemini reviews are advisory. Import results as evidence/suggestions and route them through normal MangoMe verification/approval. External reviewers must not rewrite canonical truth directly.
