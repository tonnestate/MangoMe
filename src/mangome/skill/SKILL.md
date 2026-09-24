---
name: mangome
description: Use MangoMe automatically for durable multi-agent project work, including resuming existing work, planning mutations, evidence, verification, and handoff. Apply whenever work may change or continue a MangoMe-managed project; the user does not need to know MangoMe commands or vocabulary.
---

# MangoMe Agent Skill

MangoMe is the canonical operational-memory system for durable multi-agent projects: document store, work graph, state machine, evidence/provenance ledger and execution context source.

## Zero-touch user rule

Ordinary user intent is sufficient to enter MangoMe. Never require the user to say “start Big Bang”, create a contract, create a slice, call `begin_work`, or otherwise operate MangoMe vocabulary manually. On project-changing work, inspect `workspace_status` and existing canonical state yourself. Unknown managed workspaces are automatically attached/discovered by the runtime. Translate user intent into the existing MangoMe flow; ask the user only when genuine semantic ambiguity, authorization, or a protected decision requires it.

Do not treat a missing prior Big-Bang command as a user error. Discovery/bootstrap is an operability responsibility, not a user workflow step.

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
14. **Final verification requires independent observation.** Worker-authored Evidence plus later attestation is not enough for `VERIFIED`; use AV/1 verifier observations.
15. **WAIVED requires owner approval.** Never waive a gate without an approved `WAIVE_GATE` decision.
16. **No self-verification.** The last executing actor may not verify its own DONE claim or submit its own independent AV/1 observation.
17. **ACCEPTED is explicit.** Authorized acceptance is separate from verification and requires approved `ACCEPT_SLICE` state.
18. **Close obsolete plans.** Stale plans create stale collision traffic.
19. **Do not invent missing truth.** Keep ambiguity `UNRESOLVED` / `SUGGESTED` until evidence or authorized confirmation exists.

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

For a bounded task in a family that already has an effective specification, `begin_work` may compose intake + plan + slice start. Treat it as a convenience surface only: it must still persist the normal Request, Plan and Slice and must never be used to bypass specification, plan binding, evidence or assurance rules.

## Compact context / UAI/1

When the host supports UAI/1, prefer `compile_uai_context` for expensive workers that do not need the verbose execution-context shape. UAI/1 is a disposable representation of MangoMe truth, not a replacement for canonical documents.

Rules:

1. Bind worker output to the supplied `semantic_hash`.
2. Prefer structured `UAI/1R` actions over administrative prose when the worker can comply.
3. Use `decode_uai_result` before interpreting a result.
4. Use `render_uai_result` for deterministic English/German human output where useful.
5. Never apply decoded actions directly. Route progress, artifacts, evidence and DONE claims through the normal MangoMe tools and invariants.
6. A hash mismatch means stale/tampered context; do not silently accept it.
7. Token estimates from the compiler are heuristic only. Record provider-reported token counts in `ExecutionReceipt` for real routing/economic decisions.

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

When Evidence should be reusable across time, prefer an RB/1 reproduction binding rather than prose. Run the check in the real execution environment first, then record its command/exit code and bind the relevant input hashes:

```text
build_reproduction_binding
→ submit_evidence(payload={"reproduction": ...})
→ attest_evidence
```

`build_reproduction_binding` never executes the command and never reads environment-variable values. It records names only and rejects sensitive-looking environment names. `evidence_freshness` may later classify the binding as `REUSABLE`, `STALE`, `UNKNOWN`, `UNBOUND` or `INADMISSIBLE`, but freshness never upgrades assurance and never proves cross-slice semantic coverage.

For substantive DONE verification, first build the deterministic review brief:

```text
completion_review(slice_id=..., changed_paths=[...])
```

Treat worker reports and worker-authored Evidence as claims to inspect. The verifier/host must rerun or otherwise observe each load-bearing check it relies on. Record the observation with the verifier capability:

```text
submit_verification_observation(
  observation_type=REPLAY | DIFF | SCOPE | SPEC_CHECK | RUNTIME | ARTIFACT | OTHER,
  status=PASS | FAIL | UNVERIFIABLE,
  ...
)
```

`UNVERIFIABLE` maps to `UNKNOWN`, never PASS. `REPLAY` requires an intact RB/1 reproduction binding. MangoMe records the observation but does not execute the command itself. Never place `verification_observation` inside generic `submit_evidence`; that namespace is reserved for the verifier-capability path. If AV/1 Evidence carries RB/1, final verification live-checks the binding again immediately before the assurance CAS write and blocks stale/unknown context.

A gate may then become PASS using Evidence that includes an independent AV/1 observed PASS:

```text
set_gate(status=PASS, evidence_ids=[...])
```

Final verification remains a separate transition:

```text
verify_slice
```

For v0.1.7, every PASS gate must contain at least one independent AV/1 observed PASS Evidence item. A gateless Slice requires one in the explicit proof set. Changed tests or scope deviations are review signals, not automatic findings of fraud.

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

Big-Bang discovery is normally automatic on first attachment of an unknown managed workspace. Do not ask the user to invoke it manually. `bigbang_scan` remains available as an explicit diagnostic/maintenance tool and is non-destructive across configured filesystem roots and optional Git metadata.

`reconcile_bigbang` matches discovery against canonical state without semantic mutation. Candidates, collisions and unresolved items remain explicit. Automatic attachment never promotes ambiguous candidates into contract/specification truth.

## Schema evolution and maintenance

Readers can lazily understand older schema documents. Use `migrate_schema` for an explicit dry-run or persistence migration. Use `maintenance_diagnose` for stale-plan candidates, ID collisions, open approvals and suggested relations. Diagnostics must not silently change semantic truth.

## External model reconciliation

External ChatGPT/Claude/Gemini reviews are advisory. Import results as evidence/suggestions and route them through normal MangoMe verification/approval. External reviewers must not rewrite canonical truth directly.
