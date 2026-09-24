# Filesystem inventory and proof freshness

MangoMe 0.1.5 adds a deterministic filesystem inventory intended to reduce repeated AI audits without turning historical prose into truth.

The core rule is:

> Reuse reproducible proof, not previous AI conclusions.

## What the scanner records

`filesystem_scan` walks explicitly supplied roots and persists only observable filesystem facts:

- absolute and relative path;
- file role (`SOURCE`, `TEST`, `CONTRACT`, `AUDIT_OR_REPORT`, `WORKFLOW`, `CONFIG`, `DOCUMENTATION`, `OTHER`);
- SHA-256 when the file is within the configured hash bound;
- size and nanosecond mtime;
- lexically detected declared contract/work IDs;
- nearest discovered Git repository root and HEAD;
- whether the file is currently present.

Sensitive/key files and common secret/cache/build directories are excluded. Useful hidden work directories such as `.github`, `.gitlab`, and `.devcontainer` are not discarded merely because they are hidden.

The scanner does not create contracts, slices, verification, or acceptance.

## Incremental behavior

Each path has a stable filesystem-entry identity. Unchanged entries are not rewritten. A complete rescan marks previously indexed files that disappeared as not present. Each root also receives a deterministic tree hash and scan summary.

This allows later work to query a shared inventory instead of rescanning the repository separately for every contract.

## Reference lookup

`filesystem_references(declared_id)` returns current indexed files that lexically mention a declared ID. This is navigation only. A filename or code comment referencing a contract is not proof that the contract was implemented.

Typical use:

```text
legacy contract id
    -> filesystem reference lookup
    -> likely source/tests/config/workflows
    -> targeted verification
```

## Proof freshness

Existing MangoMe Evidence can bind itself to concrete filesystem facts through the existing `payload` field:

```json
{
  "filesystem_bindings": [
    {
      "path": "/opt/app/src/policy.py",
      "sha256": "<sha256>"
    },
    {
      "path": "/opt/app/tests/test_policy.py",
      "sha256": "<sha256>"
    }
  ]
}
```

`evidence_freshness(evidence_id)` then checks whether the proof is still reusable.

It returns:

- `REUSABLE`: attested PASS evidence and all bound hashes still match;
- `STALE`: a bound file changed or disappeared;
- `UNKNOWN`: a binding cannot currently be checked;
- `UNBOUND`: no reproducible filesystem binding exists;
- `INADMISSIBLE`: for example a `CLAIM`, unattested evidence, or non-PASS result.

By default freshness performs a live SHA-256 check of the bound files, so reuse does not depend on trusting an old scan timestamp.

## What this deliberately does not do

A historical AI audit remains a claim/report. It is not promoted because it says “implemented”, “verified”, or “all tests passed”.

Freshness also does not create `VERIFIED` or `ACCEPTED`. It only answers whether an already attested reproducible proof remains unchanged. The normal MangoMe verification and acceptance rules still apply.

MangoMe 0.1.5 therefore establishes the cheap deterministic substrate for proof reuse while avoiding fabricated historical slice provenance or automatic cross-slice semantic equivalence.
