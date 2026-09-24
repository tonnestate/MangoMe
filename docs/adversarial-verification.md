# AV/1 adversarial completion verification

MangoMe v0.1.7 adds a stricter final-verification profile for completed work.

The governing rule is:

> A completion report is a set of claims. Verification requires independently observed Evidence.

AV/1 does not create a new domain entity and does not replace MangoMe's existing assurance states. It is a structured Evidence convention plus stricter `verify_slice` enforcement.

## Why it exists

Before v0.1.7, MangoMe already separated `DONE_CLAIMED` from `VERIFIED`, required verifier capabilities, prohibited the last executor from verifying its own DONE claim, and required attested PASS Evidence. A remaining gap was that a verifier could attest PASS Evidence originally authored by the worker without recording an independent observation of the claimed outcome.

AV/1 closes that gap for final verification.

## Deterministic review brief

`completion_review(slice_id, changed_paths=None)` returns the currently persisted verification surface:

- the Slice execution and assurance state;
- the last executor and bound Plan;
- Plan `expected_scope`, `expected_artifacts`, and acceptance expectations;
- current Specification acceptance criteria and required Evidence;
- persisted Claims for the Slice, returned verbatim;
- worker-authored Evidence ids;
- trusted independent AV/1 observations already recorded;
- optional deterministic scope/test-change signals for verifier-observed changed paths.

MangoMe does not claim to extract the semantic meaning of free-text DONE prose deterministically. A host or verifier may decompose prose into concrete checks, but any resulting observation must still be persisted as Evidence.

## Change-set review

When `changed_paths` are supplied, MangoMe compares them with the Plan's `expected_scope`.

Possible signals include:

- `SCOPE_DEVIATION` — at least one supplied changed path falls outside declared scope;
- `TEST_CHANGE_REVIEW_REQUIRED` — a supplied changed path looks like a test/spec file.

These are review signals only. A changed test can be correct and necessary; an out-of-scope path can be justified. MangoMe does not label either condition as fraud or failure automatically.

## Independent observations

`submit_verification_observation` requires a verifier capability and rejects the last executing actor.

AV/1 observation types are:

- `REPLAY`
- `DIFF`
- `SCOPE`
- `SPEC_CHECK`
- `RUNTIME`
- `ARTIFACT`
- `OTHER`

Observation states are:

- `PASS`
- `FAIL`
- `UNVERIFIABLE`

`UNVERIFIABLE` is persisted as `EvidenceVerdict.UNKNOWN`. It is never converted to PASS.

Each observation is stored inside the existing Evidence payload:

```json
{
  "verification_observation": {
    "version": "AV/1",
    "claim": "runtime check passes",
    "observation_type": "REPLAY",
    "status": "PASS",
    "observed_by": "verifier-b",
    "original_evidence_id": "...",
    "observed_at": "..."
  },
  "reproduction": {
    "version": "RB/1",
    "...": "..."
  }
}
```

The Evidence itself is written by the verifier actor and immediately receives verifier attestation through the same runtime capability used to authorize the observation.

## Replay and RB/1

A `REPLAY` observation must carry an intact RB/1 reproduction binding. MangoMe validates the RB/1 fingerprint before accepting the observation.

This still does not mean MangoMe executed the command. The verifier or host must actually run the check and then submit what it observed. MangoMe records and enforces the resulting assurance boundary; it is not a general shell runner or sandbox.

## Final verification rule

For a Slice with PASS gates, every PASS gate must include at least one independent AV/1 observed PASS Evidence item before `verify_slice` can succeed.

For a gateless Slice, the explicit proof set passed to `verify_slice` must include at least one independent AV/1 observed PASS Evidence item.

An explicitly `WAIVED` gate remains an owner-governed exception: the approved `WAIVE_GATE` decision removes that gate's Evidence requirement.

Worker Evidence may still be retained, attested, inspected, and attached to gates. It simply does not substitute for independent final observation.

Existing Slices that were already `VERIFIED` before v0.1.7 are not rewritten. The stronger rule applies when `verify_slice` is invoked under v0.1.7.

## v0.1.7.1 provenance and final-time freshness hardening

The `verification_observation` payload namespace is reserved for `submit_verification_observation`. Generic `submit_evidence` calls that try to populate it are rejected. This prevents caller-declared `actor_id` values from being shaped like independent AV/1 observations and then upgraded by later attestation.

AV/1 independence also requires `VERIFIER_ATTESTED` trust. Owner attestation remains valid for ordinary Evidence and governed waivers/acceptance, but it does not manufacture verifier provenance. Dedicated AV/1 observations carry a `provenance = VERIFIER_CAPABILITY_PATH` marker; older or directly injected AV/1-shaped payloads without that marker are not accepted as independent observations.

Immediately before the `VERIFIED` compare-and-swap write, MangoMe live-checks every independent AV/1 PASS Evidence item used for the transition that carries an RB/1 reproduction binding. The binding must be `REUSABLE`; `STALE`, `UNKNOWN`, `UNBOUND`, or `INADMISSIBLE` blocks verification. This catches the practical case where an input or bound output changed after the verifier observed it but before final assurance commit.

This is intentionally not described as a fully atomic filesystem-plus-database transaction. MangoMe's slice update remains revision-CAS protected; runtimes that require a zero-width TOCTOU window across external artifact stores must additionally provide isolation, locking, immutable artifact addressing, or an equivalent storage-level mechanism.

## Relationship to RB/1 freshness

AV/1 and RB/1 answer different questions:

```text
AV/1:  Who independently observed the claimed outcome, and what did they observe?
RB/1:  Is the recorded reproduction context still bound to the same declared inputs?
```

Neither mechanism creates `ACCEPTED`. Acceptance remains a distinct authorized decision after verification.

## Third-party influence

The design was informed by the `fable-judge` skill in [Sahir619/fable-method](https://github.com/Sahir619/fable-method), particularly its claim-oriented verification stance, independent re-observation of claimed checks, diff/scope inspection, and attention to weakened tests and false completion reports.

MangoMe implements these concepts independently inside its existing Evidence, Verification and Acceptance model. It does not adopt Fable's `VERIFIED / VERIFIED WITH CAVEATS / REFUTED` verdict lifecycle and does not bundle Fable's eval fixtures.

See `THIRD_PARTY_NOTICES.md` for attribution and license information.
